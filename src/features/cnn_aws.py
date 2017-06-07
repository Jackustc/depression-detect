from __future__ import print_function
import boto
import os
import numpy as np
from sklearn.model_selection import train_test_split
from skimage.measure import block_reduce  # for downsampling
np.random.seed(15)  # for reproducibility

from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Flatten
from keras.layers import Conv2D, MaxPooling2D
from keras.utils import np_utils
from keras import backend as K
from keras.optimizers import SGD
K.set_image_dim_ordering('th')
# access_key = os.environ['AWS_ACCESS_KEY_ID']
# access_secret_key = os.environ['AWS_SECRET_ACCESS_KEY']


"""
CNN to classify spectrograms of normal particpants (0) or depressed particpants (1).
Using Theano with TensorFlow image_dim_ordering:
(# images, # channels, # rows, # cols)
(3040, 1, 513, 125) for the X images below
"""

def retrieve_from_bucket(file):
    """
    Download matrices from S3 bucket
    """
    conn = boto.connect_s3(access_key, access_secret_key)
    bucket = conn.get_bucket('depression-detect')
    file_key = bucket.get_key(file)
    file_key.get_contents_to_filename(file)
    X = np.load(file)
    return X

def preprocess(X_train, X_test):
    """
    Convert from float64 to float32 for speed.
    """
    X_train = X_train.astype('float32')
    X_test = X_test.astype('float32')
    # normalize to decibels relative to full scale (dBFS) for the 4 sec clip
    X_train = np.array([(X - X.min()) / (X.max() - X.min()) for X in X_train])
    X_test = np.array([(X - X.min()) / (X.max() - X.min()) for X in X_test])
    return X_train, X_test


def train_test(X_train, y_train, X_test, y_test, nb_classes):
    """
    Split the X, y datasets into training and test sets based on desired test size.

    Parameters
    ----------
    X : array
        X features (represented by spectrogram matrix)
    y : array
        y labels (0 for normal; 1 for depressed)
    nb_classes : int
        number of classes being classified (2 for a binary label)
    test_size : float
        perecentge of data to include in test set

    Returns
    -------
    X_train and X_test : arrays
    Y_train and Y_test : arrays
        binary class matrices
    """
    print('X_train shape:', X_train.shape)
    print('Train on {} samples, validate on {}'.format(X_train.shape[0], X_test.shape[0]))

    X_train, X_test = preprocess(X_train, X_test)

    # Convert class vectors to binary class matrices
    Y_train = np_utils.to_categorical(y_train, nb_classes)
    Y_test = np_utils.to_categorical(y_test, nb_classes)

    return X_train, X_test, Y_train, Y_test


def keras_img_prep(X_train, X_test, img_dep, img_rows, img_cols):
    """
    Reshape feature matrices for Keras' expexcted input dimensions.
    For 'th' (Theano) dim_order, the model expects dimensions:
    (# channels, # images, # rows, # cols).
    """
    if K.image_dim_ordering() == 'th':
        X_train = X_train.reshape(X_train.shape[0], 1, img_rows, img_cols)
        X_test = X_test.reshape(X_test.shape[0], 1, img_rows, img_cols)
        input_shape = (1, img_rows, img_cols)
    else:
        X_train = X_train.reshape(X_train.shape[0], img_rows, img_cols, 1)
        X_test = X_test.reshape(X_test.shape[0], img_rows, img_cols, 1)
        input_shape = (img_rows, img_cols, 1)
    return X_train, X_test, input_shape


def cnn(X_train, y_train, X_test, y_test, batch_size, nb_classes, epochs, input_shape):
    """
    This Convolutional Neural Net architecture for classifying the audio clips
    as normal (0) or depressed (1).
    """
    model = Sequential()

    # model.add(Conv2D(32, (7, 7), input_shape=input_shape, activation='relu'))
    #
    # model.add(Flatten())
    # model.add(Dense(128, activation='relu'))
    # model.add(Dense(128, activation='relu'))
    # model.add(Dense(128, activation='relu'))
    # model.add(Activation('softmax'))

    model.add(Conv2D(32, (57, 6), padding='valid', strides=1, input_shape=input_shape, activation='relu', kernel_initializer='random_uniform'))
    model.add(MaxPooling2D(pool_size=(4,3), strides=(1,3)))
    model.add(Conv2D(32, (1, 3), padding='valid', strides=1, input_shape=input_shape, activation='relu'))
    model.add(MaxPooling2D(pool_size=(1,3), strides=(1,3)))

    model.add(Flatten())
    model.add(Dense(128, activation='relu'))
    model.add(Dense(128, activation='relu'))
    model.add(Dense(nb_classes))
    model.add(Activation('softmax'))

    # sgd = SGD(lr=0.001, decay=1e-6, momentum=1.0)
    model.compile(loss='categorical_crossentropy',
                  optimizer='adadelta',
                  metrics=['accuracy'])

    model.fit(X_train, y_train, batch_size=batch_size, epochs=epochs,
              verbose=1, validation_data=(X_test, y_test))

    # Evaluate accuracy on test and train sets
    score_train = model.evaluate(X_train, y_train, verbose=0)
    print('Train accuracy:', score_train[1])
    score_test = model.evaluate(X_test, y_test, verbose=0)
    print('Test accuracy:', score_test[1])

    return model


def model_performance(model, X_train, X_test, y_train, y_test):
    y_test_pred = model.predict_classes(X_test)
    y_train_pred = model.predict_classes(X_train)

    y_test_pred_proba = model.predict_proba(X_test)
    y_train_pred_proba = model.predict_proba(X_train)

    return y_train_pred, y_test_pred, y_train_pred_proba, y_test_pred_proba


if __name__ == '__main__':
    # # Uncomment to load from S3 bucket
    X_train = retrieve_from_bucket('train_samples.npz')
    y_train = retrieve_from_bucket('train_labels.npz')
    X_test = retrieve_from_bucket('test_samples.npz')
    y_test = retrieve_from_bucket('test_labels.npz')

    # # Once stored locally, access with the following

    X_train, y_train, X_test, y_test = np.load('~/depression-detect/data/processed/train_samples.npz')['arr_0'], np.load('~/depression-detect/data/processed/train_labels.npz')['arr_0'], np.load('~/depression-detect/data/processed/test_samples.npz')['arr_0'], np.load('~/depression-detect/data/processed/test_labels.npz')['arr_0']

    # # troubleshooting -- 80 samples from 4 particpants
    # samples = []
    # depressed1 = np.load('/Users/ky/Desktop/depression-detect/data/processed/D321.npz')
    # for key in depressed1.keys():
    #     samples.append(depressed1[key])
    # depressed1 = np.load('/Users/ky/Desktop/depression-detect/data/processed/D330.npz')
    # for key in depressed1.keys():
    #     samples.append(depressed1[key])
    # normal1 = np.load('/Users/ky/Desktop/depression-detect/data/processed/N310.npz')
    # for key in normal1.keys():
    #     samples.append(normal1[key])
    # normal2 = np.load('/Users/ky/Desktop/depression-detect/data/processed/N429.npz')
    # for key in normal2.keys():
    #     samples.append(normal2[key])
    #
    # X = np.array(samples)
    # y = np.concatenate((np.ones(80), np.zeros(80)))

    # CNN parameters
    batch_size = 8
    nb_classes = 2
    epochs = 4

    # normalalize data and prep for Keras
    X_train, X_test, y_train, y_test = train_test(X_train, y_train, X_test, y_test, nb_classes=nb_classes)

    # specify image dimensions - 513x125x1 for spectrogram with crop size of 125 pixels
    img_rows, img_cols, img_depth = X_train.shape[1], X_train.shape[2], 1

    # prep image input for Keras
    # used Theano dim_ordering (th), (# images, # chans, # rows, # cols)
    X_train, X_test, input_shape = keras_img_prep(X_train, X_test, img_depth, img_rows, img_cols)

    print('X_train shape', X_train.shape)
    print('input shape', input_shape)

    print('image data format:', K.image_data_format())

    # run CNN
    model = cnn(X_train, y_train, X_test, y_test, batch_size, nb_classes, epochs, input_shape)

    # evaluate model
    y_train_pred, y_test_pred, y_train_pred_proba, y_test_pred_proba = model_performance(model, X_train, X_test, y_train, y_test)